"""The risk quantiles of R24's veil loop on the real 3.29.3.3 boots (ticket #349, #145).

Skips cleanly when the dump is not cached (CI has it). The plan is the loop graph of ticket #145 (the Veiled Chaos Orb only from a state that
holds the lock; the unveil, the picks and the lock craft as they come) with a restart, the planner's own way out of a state that has no way
on (a veil that drew two more prefixes leaves the item with no free prefix for the lock): solved by the solver, the risk run is the planner's
(`evaluate_risk`, with the free cost `price_offers` gave the unveil and the picks). Before #349 the step of the grid was that epsilon (5e-6
Chaos), and the 0.9 quantile and the CVaR of such a plan came back unresolved or, where the coarse grid caught them, a step wide.
"""

import datetime
import math

import pytest
from abstraction_support import real_game_data
from risk_support import simulate
from test_abstraction_veiled_real import BOOTS, LEVEL, LOCK, R24

from crafting_system.abstraction import Abstraction
from crafting_system.actions import ActionError, BenchCraft, VeiledChaosOrb
from crafting_system.cli._offers import FREE_ACTION_SHARE, free_action_cost, offer_of, price_offers
from crafting_system.cli._plan import evaluate_risk, offer_action
from crafting_system.items import tier_table
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome, solve

VEILED_CHAOS = 5.0
RESTART = 100.0


class LoopModel:
    """The solver's view of the loop graph: the veil only from a lock state, every other priced action where the game allows it, and a restart."""

    def __init__(self, ability, start, entries):
        self.ability, self.start, self.entries = ability, start, entries

    def is_goal(self, state):
        return self.ability.is_goal(state)

    def actions(self, state):
        found = []
        for entry in self.entries:
            if isinstance(entry.offer.action, VeiledChaosOrb) and not any(slot.crafted and slot.kind == LOCK for slot in state.slots):
                continue
            try:
                found.append(offer_action(self.ability, entry, state, self.start))
            except ActionError:
                pass
        if state != self.start:
            found.append(Action("restart", RESTART, (Outcome(self.start, 1),)))
        return found


@pytest.fixture(scope="module")
def plan():
    data = real_game_data()
    r24 = R24(data, tier_table(data, BOOTS))
    actions = [*r24.actions, BenchCraft(LOCK)]
    prices = PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, {"Veiled Chaos Orb": PriceEntry(VEILED_CHAOS, "test")})
    entries, _ = price_offers([offer_of(action, action.label(data), data) for action in actions], prices)
    ability = Abstraction(data, r24.goal, BOOTS, LEVEL, actions, metamods=True)
    start = ability.compress(r24.start())
    solution = solve(LoopModel(ability, start, entries), [start])
    return ability, start, entries, solution


def test_the_loop_plan_is_priced_with_an_epsilon_for_the_free_actions(plan):
    ability, start, entries, solution = plan

    assert free_action_cost(entries) == pytest.approx(VEILED_CHAOS * FREE_ACTION_SHARE)
    assert math.isfinite(solution.values[start]) and solution.error_bound < 1e-6
    assert {action.label for action in solution.policy.values()} >= {"Veiled Chaos Orb", "Unveil", "Pick 3"}


def test_the_0_9_quantile_and_the_cvar_of_the_loop_plan_resolve_with_the_epsilon_stated(plan):
    ability, start, entries, solution = plan

    risk = evaluate_risk(solution.policy, start, ability.is_goal, solution.values[start], free_cost=free_action_cost(entries))

    assert risk.success_probability.value == 1.0
    assert risk.mean.value == pytest.approx(solution.values[start], rel=1e-6)
    for estimate in (risk.p50, risk.p90, risk.cvar):
        assert math.isfinite(estimate.high)
    assert risk.grid.step == VEILED_CHAOS and risk.grid.free_allowance > 0.0 and risk.grid.free_tail > 0.0
    assert risk.p90.high - risk.p90.low <= 2 * risk.grid.free_allowance  # as wide as the epsilon's allowance, not a step
    assert risk.cvar.high - risk.cvar.low < 1e-4 * risk.cvar.value


def test_the_loop_plan_agrees_with_the_independent_simulator_within_its_stated_error(plan):
    ability, start, entries, solution = plan
    risk = evaluate_risk(solution.policy, start, ability.is_goal, solution.values[start], free_cost=free_action_cost(entries))
    runs = 100_000

    sample = simulate(solution.policy, start, ability.is_goal, runs=runs, seed=24)

    assert abs(sample.mean() - risk.mean.value) <= 5 * sample.mean_standard_error()
    for level in (0.5, 0.9):
        slack = 5 * math.sqrt(level * (1 - level) / runs)
        estimate = risk.quantiles[level]
        assert sample.cdf_at(estimate.high) >= level - slack
        assert sample.cdf_below(estimate.low) <= level + slack
    slack = 5 * sample.tail_mean_standard_error(0.9)
    assert risk.cvar.low - slack <= sample.tail_mean(0.9) <= risk.cvar.high + slack


def test_the_free_grid_is_narrower_than_what_the_epsilon_grid_gave_and_agrees_with_it(plan):
    ability, start, entries, solution = plan
    new = evaluate_risk(solution.policy, start, ability.is_goal, solution.values[start], free_cost=free_action_cost(entries))

    old = evaluate_risk(solution.policy, start, ability.is_goal, solution.values[start])  # main: the epsilon among the costs

    for level in (0.5, 0.9):
        assert old.quantiles[level].low - 1e-9 <= new.quantiles[level].low and new.quantiles[level].high <= old.quantiles[level].high + 1e-9
    assert max(old.cvar.low, new.cvar.low) <= min(old.cvar.high, new.cvar.high)  # both are certified, so they overlap
    assert new.cvar.high - new.cvar.low < old.cvar.high - old.cvar.low
