"""The solver entry point: reachable states, finite set, components in reverse topological order.

Known limits:
* The finite-state analysis (`proper_states`) settles the strongly connected components sink-first.
  It is linear for chains, DAGs and any graph of small components, and for a large cycle whose
  dead ends fall by the safety peel. Inside a large cycle, cutting a member's proof of reaching
  the goal is mended locally, but in the worst case a cut near the root of a big proof tree is
  mended again and again from inside the cycle and costs quadratic time (no linear algorithm is
  known for this almost-sure reachability on a general graph).
* `ConvergenceError` carries only the best certified bound, no partial result.
"""

import math
from array import array
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from numbers import Integral, Real

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
    a finite value to its original action (true weights, self-loop included; rebuilt from the
    solver's compact storage, so repeated successors of the offered action are merged into one
    outcome and zero-weight outcomes are dropped). `error_bound` is a
    certified relative bound: for every finite value, V(s) * (1 - error_bound) <= V*(s) <=
    V(s) * (1 + error_bound). It includes the float64 rounding of the probabilities, an
    amplification of about epsilon * value / g, so it may exceed the `tolerance` asked for, and it
    is `math.inf` for a component whose upper side cannot be certified (values are still returned).
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
    check_options(tolerance, direct_solve_limit, max_sweeps)
    graph = build_graph(model, starts)
    alive, in_y = proper_states(graph)
    count = len(graph.states)

    offsets, edges = array("q", [0]), array("i")  # state graph over the retained actions only
    targets, tstart, first = graph.targets, graph.tstart, graph.first
    for state in range(count):
        if in_y[state]:
            for k in range(first[state], first[state + 1]):
                if alive[k]:
                    edges.extend(targets[tstart[k] : tstart[k + 1]])
        offsets.append(len(edges))

    value = [math.inf] * count
    lo = [1.0] * count
    hi = [1.0] * count
    choice = [-1] * count
    total_error = 0.0
    roots = (state for state in range(count) if in_y[state])
    for component in strongly_connected_components(offsets, edges, roots):
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
            states[i]: graph.original_action(choice[i])
            for i in range(count)
            if in_y[i] and not graph.goal[i]
        },
        error_bound=total_error,
    )


def check_options(tolerance: object, direct_solve_limit: object, max_sweeps: object) -> None:
    """Raise `ValueError` for a `tolerance`, `direct_solve_limit` or `max_sweeps` `solve` cannot use."""
    if isinstance(tolerance, bool) or not isinstance(tolerance, Real) or not (
        math.isfinite(tolerance) and tolerance > 0
    ):
        raise ValueError(f"tolerance must be finite and above zero, got {tolerance!r}")
    if isinstance(max_sweeps, bool) or not isinstance(max_sweeps, Integral) or max_sweeps < 1:
        raise ValueError(f"max_sweeps must be an integer of at least 1, got {max_sweeps!r}")
    if (
        isinstance(direct_solve_limit, bool)
        or not isinstance(direct_solve_limit, Integral)
        or direct_solve_limit < 0
    ):
        raise ValueError(f"direct_solve_limit must be an integer of at least 0, got {direct_solve_limit!r}")
