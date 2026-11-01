"""Runs a policy on concrete items (ADR-0019). May import only: data, rules, items, actions, abstraction, solver, risk.

Verification layer 2: an independent check of the abstraction kernel. It is written from the
documented behaviour of the actions (`action.outcomes(data, item).sample(rng)`) and in fact imports
none of `abstraction`, `solver` or `risk` (`tests/test_simulator_independence.py` guards that). The
goal check and the costs are passed in by the caller, so it does not import `prices` or `targets`.

`simulate(data, policy, start, is_goal, runs=..., seed=...)` returns a `SimulationReport`: the
success rate (Wilson interval), the mean total cost with a confidence interval, the cost of the
successful runs, the mean number of steps and the cost of every run, from which `quantile(level)`
reads a quantile and `cvar(level)` the mean of the worst share. A policy is a function from a
concrete item to a `Step` (an action and what one use of it costs) or to None to stop. The
intervals are normal approximations, good for thousands of runs.

Public names: `Action`, `Policy`, `SampledEstimate`, `Sampler`, `SimulationReport`, `Step`, `simulate`.
"""

from ._estimate import SampledEstimate
from ._report import SimulationReport
from ._simulate import simulate
from ._step import Action, Policy, Sampler, Step

__all__ = ["Action", "Policy", "SampledEstimate", "Sampler", "SimulationReport", "Step", "simulate"]
