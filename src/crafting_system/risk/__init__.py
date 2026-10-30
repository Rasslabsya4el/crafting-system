"""Metrics of a fixed policy (ADR-0006). May import only: data, rules, items, actions, abstraction, solver.

`evaluate(policy, start, is_goal)` returns the success probability and the mean, variance,
quantiles and CVaR of the total cost of reaching a goal, each with a certified interval. Mean and
variance come from the solver (through its public API only); quantiles and CVaR from a budget DP
over a cost grid. Like the solver it is generic: states are any hashable objects.
"""

from ._evaluate import evaluate
from ._report import Estimate, GridInfo, RiskReport

__all__ = ["Estimate", "GridInfo", "RiskReport", "evaluate"]
