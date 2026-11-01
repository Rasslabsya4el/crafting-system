"""`simulate` with the real `ChaosOrb` and `HarvestReforge` on the fixture amulet, against exact chances.

The start item is `amulet(fractured_resist())`. Both rerolls keep only the fractured mod, so what
one step can leave behind is the same on every step and `outcomes.chance_all` gives its exact
chances as `Fraction`s. Repeating one step until a condition holds is then geometric. Stated
tolerances, each at five standard errors so a correct result fails about once in 1.7 million runs
(the seeds are fixed, so a run is repeatable):

* mean cost: |report mean - exact value| <= 5 * the report's own standard error of the mean;
* mean steps: within 5 sd(steps) / sqrt(N) of the exact value, sd(steps) = sqrt(1-q) / q for a
  geometric count with chance q (the mixed policy: solved exactly with `steps_mean_and_sd`);
* success rate 1: exact, no run may fail.

N = 3_000 runs, about 20 to 30 real draws each. The long runs use `Memoized` actions (the exact
outcomes are built once per start item); one run uses the plain actions, with N = 500.
"""

import dataclasses
import functools
import math

import pytest
from actions_support import AMULET, RESIST, TARGET, amulet, fractured_resist, roll
from items_support import item
from simulator_support import DATA, Draw, Memoized, holds_target, paid, solve_chain, steps_mean_and_sd

from crafting_system.actions import ChaosOrb, HarvestReforge, NotApplicableError, OutOfScopeError
from crafting_system.items import Rarity
from crafting_system.simulator import Step, simulate

N = 3_000
PLAIN_N = 500
CHAOS_COST, HARVEST_COST = 1.0, 3.0
OTHER = "ItemFoundRarityIncreasePrefix3"  # a prefix an amulet at item level 86 can roll
START = amulet(fractured_resist())


def holds(mod_id):
    return lambda item: any(entry.mod_id == mod_id for entry in item.mods)


@functools.cache
def chances(action):
    """The exact chance that one use of `action` on START leaves TARGET, OTHER, and both."""
    outcomes = action.outcomes(DATA, START)
    return (
        outcomes.chance_all([TARGET]),
        outcomes.chance_all([OTHER]),
        outcomes.chance_all([TARGET, OTHER]),
    )


def repeat_until_target(action, cost, *, runs, seed):
    step = Step(action, cost)
    return simulate(DATA, lambda item: step, START, holds_target, runs=runs, seed=seed)


def geometric_checks(report, q, cost, runs):
    sd_steps = math.sqrt(1 - q) / q
    assert report.successes == runs and report.stopped == 0 and report.unfinished == 0
    assert report.success_rate.value == 1.0
    assert report.cost.agrees_with(cost / q)
    assert abs(report.mean_steps - 1 / q) <= 5 * sd_steps / math.sqrt(runs)


def test_chaos_orb_until_the_target_costs_the_step_over_the_chance():
    q = float(chances(ChaosOrb())[0])

    report = repeat_until_target(Memoized(ChaosOrb()), CHAOS_COST, runs=N, seed=2501)

    assert 0 < q < 1
    geometric_checks(report, q, CHAOS_COST, N)


def test_the_harvest_reforge_until_the_target_costs_the_step_over_the_chance():
    q = float(chances(HarvestReforge("lightning"))[0])

    report = repeat_until_target(Memoized(HarvestReforge("lightning")), HARVEST_COST, runs=N, seed=2502)

    assert 0 < q < 1
    geometric_checks(report, q, HARVEST_COST, N)


def test_the_plain_actions_without_a_cache_agree_too():
    q = float(chances(HarvestReforge("lightning"))[0])

    report = repeat_until_target(HarvestReforge("lightning"), HARVEST_COST, runs=PLAIN_N, seed=2503)

    geometric_checks(report, q, HARVEST_COST, PLAIN_N)


def test_a_policy_that_picks_the_action_by_the_item_matches_the_exact_chain():
    """Harvest reforge on an item without the other prefix, Chaos Orb once it holds it, until TARGET.

    After any step the item is in one of three classes: it holds TARGET (the goal), it holds OTHER
    only (P), or neither (N); the chances of each come from `chance_all` of the action used. The
    start is class N. The chain N -> {goal, P, N} (Harvest) and P -> {goal, P, N} (Chaos) is solved
    exactly in Fractions for the expected cost, the expected steps and the sd of the steps.
    """
    harvest, chaos = HarvestReforge("lightning"), ChaosOrb()
    memo = {harvest: Memoized(harvest), chaos: Memoized(chaos)}

    def row(action):
        target, other, both = chances(action)
        return (("goal", target), ("P", other - both), ("N", 1 - target - (other - both)))

    chain = {"N": (HARVEST_COST, row(harvest)), "P": (CHAOS_COST, row(chaos))}
    assert all(weight > 0 for _, (_, outgoing) in chain.items() for _, weight in outgoing)
    expected_cost = float(solve_chain(chain, paid)["N"])
    expected_steps, steps_sd = steps_mean_and_sd(chain, "N")

    def policy(item):
        if holds(OTHER)(item):
            return Step(memo[chaos], CHAOS_COST)
        return Step(memo[harvest], HARVEST_COST)

    report = simulate(DATA, policy, START, holds_target, runs=N, seed=2504)

    assert report.successes == N
    assert report.cost.agrees_with(expected_cost)
    assert abs(report.mean_steps - expected_steps) <= 5 * steps_sd / math.sqrt(N)
    # the exact model really mixes: pricing every step as a Harvest reforge would give another total
    assert abs(expected_cost - HARVEST_COST * expected_steps) > 1.0


def test_a_chaos_orb_on_a_magic_item_is_refused_and_the_refusal_propagates():
    magic = amulet(roll(RESIST), rarity=Rarity.MAGIC)

    with pytest.raises(NotApplicableError):
        simulate(DATA, lambda item: Step(ChaosOrb(), 1.0), magic, holds_target, runs=2, seed=1)


def test_an_item_no_rule_covers_raises_out_of_scope_and_it_propagates():
    jewel = dataclasses.replace(DATA.base_items[AMULET], item_class="Jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, AMULET: jewel})
    start = item(roll(RESIST), base_id=AMULET, item_level=86)

    with pytest.raises(OutOfScopeError):
        simulate(data, lambda item: Step(ChaosOrb(), 1.0), start, holds_target, runs=2, seed=1)


class CorruptingAction:
    """A fake action whose result is the item corrupted, so that the next real action on it is refused."""

    def outcomes(self, data, item):
        corrupted = item.changed(data, corrupted=True)
        return Draw([corrupted], [1])


def test_a_refusal_in_the_middle_of_a_run_propagates():
    """The first step is a fake that corrupts the item; the Chaos Orb the policy then applies is refused."""

    def policy(item):
        return Step(ChaosOrb(), 1.0) if item.corrupted else Step(CorruptingAction(), 1.0)

    with pytest.raises(NotApplicableError):
        simulate(DATA, policy, START, holds_target, runs=2, seed=1)
