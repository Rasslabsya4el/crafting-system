"""The solver entry point: reachable states, finite set, components in reverse topological order."""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ._certify import ConvergenceError, rounding_allowance
from ._component import backup_single, build_bellman, solve_cyclic
from ._graph import build_graph, proper_states
from ._model import Action, Model
from ._scc import strongly_connected_components


@dataclass(frozen=True, slots=True)
class Solution[S]:
    """What `solve` returns.

    `values` holds the expected remaining cost of every reachable state: 0.0 for goals and
    `math.inf` for states with no proper policy. `policy` maps each reachable non-goal state with
    a finite value to its original action (true weights, self-loop included). `error_bound` is a
    certified relative bound: for every finite value, V(s) * (1 - error_bound) <= V*(s) <=
    V(s) * (1 + error_bound).
    """

    values: Mapping[S, float]
    policy: Mapping[S, Action[S]]
    error_bound: float


def solve[S](
    model: Model[S],
    starts: Iterable[S],
    *,
    tolerance: float = 1e-10,
    direct_solve_limit: int = 64,
    max_sweeps: int = 100_000,
) -> Solution[S]:
    """Minimise the mean cost to a goal from every state reachable from `starts`.

    `tolerance` is the stopping threshold on each cyclic component's own certified relative
    error; components of at most `direct_solve_limit` states are solved by policy iteration
    first (0 forces value iteration everywhere). Raises `ConvergenceError` when a component
    cannot reach `tolerance` within `max_sweeps` sweeps.
    """
    graph = build_graph(model, starts)
    alive, in_y = proper_states(graph)
    count = len(graph.states)

    adjacency: list[list[int]] = [[] for _ in range(count)]
    for state in range(count):
        if in_y[state]:
            adjacency[state] = [
                j for k in graph.state_actions[state] if alive[k] for j in graph.succ[k]
            ]

    value = [math.inf] * count
    lo = [1.0] * count
    hi = [1.0] * count
    choice = [-1] * count
    total_error = 0.0
    roots = (state for state in range(count) if in_y[state])
    for component in strongly_connected_components(adjacency, roots):
        if len(component) == 1 and graph.goal[component[0]]:
            value[component[0]] = 0.0
            continue
        bellman = build_bellman(graph, alive, component, value, lo, hi)
        rho = rounding_allowance(bellman.terms)
        if len(component) == 1:
            value[component[0]], choice[component[0]] = backup_single(bellman)
            lower = upper = 1.0
            converged = True
        else:
            result = solve_cyclic(bellman, tolerance, direct_solve_limit, max_sweeps)
            for state, found, action in zip(component, result.values, result.choice):
                value[state], choice[state] = found, action
            lower, upper, converged = result.lower, result.upper, result.converged
        low = bellman.low_d * lower * (1.0 - rho)
        high = bellman.high_d * upper * (1.0 + rho)
        for state in component:
            lo[state], hi[state] = low, high
        total_error = max(total_error, 1.0 - low, high - 1.0)
        if not converged:
            raise ConvergenceError(
                f"a component of {len(component)} states did not reach tolerance {tolerance} "
                f"within {max_sweeps} sweeps",
                total_error,
            )

    states = graph.states
    return Solution(
        values={states[i]: value[i] for i in range(count)},
        policy={
            states[i]: graph.original[choice[i]]
            for i in range(count)
            if in_y[i] and not graph.goal[i]
        },
        error_bound=total_error,
    )
