"""Metrics of a fixed policy (ADR-0006). May import only: data, rules, items, actions, abstraction, solver.

`evaluate(policy, start, is_goal)` returns the success probability and the mean, variance,
quantiles and CVaR of the total cost of reaching a goal, each with a certified interval. Mean and
variance come from the solver (through its public API only); quantiles and CVaR from a budget DP
over a cost grid. Like the solver it is generic: states are any hashable objects.

A policy may list `extra_inputs` (ADR-0022): the run of each input state is paid on every execution
of the action. Then the mean and variance come from linear systems of the policy tree (`_inputs`),
not from the solver, and the distribution from a budget DP with each input's pmf convolved in.

Rule axes (ADR-0012 amended, ADR-0022; `_readings`). `solve_readings` takes one ordinary model per reading of the rule axes,
solves each, evaluates every optimal policy under every reading and returns the plan, its cost interval over the whole
grid, the route with the smallest worst case, the certified bracket of the robust optimum and the best route without the
actions left out.

`expected_total(policy, start, is_goal, weight)` is the expected total of a weight over the executions of a fixed policy, the
runs of its inputs included: with weight 1 on the recombinations, the expected number of recombinations (ticket #221).
"""

from ._evaluate import evaluate
from ._free import is_free as is_free_cost
from ._readings import Baseline, IntervalReport, Route, has_inputs, solve_readings
from ._report import Estimate, GridInfo, RiskReport
from ._visits import expected_total

__all__ = [
    "Baseline",
    "Estimate",
    "GridInfo",
    "IntervalReport",
    "RiskReport",
    "Route",
    "evaluate",
    "expected_total",
    "has_inputs",
    "is_free_cost",
    "solve_readings",
]
