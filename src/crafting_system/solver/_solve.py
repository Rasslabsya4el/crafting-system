"""The solver entry point: reachable states, finite set, components in reverse topological order.

Known limits:
* The finite-state analysis (`proper_states`) settles the strongly connected components sink-first.
  It is linear for chains, DAGs and any graph of small components, and for a large cycle whose
  dead ends fall by the safety peel. Inside a large cycle, cutting a member's proof of reaching
  the goal is mended locally, but in the worst case a cut near the root of a big proof tree is
  mended again and again from inside the cycle and costs quadratic time (no linear algorithm is
  known for this almost-sure reachability on a general graph).
* `ConvergenceError` carries only the best certified bound, no partial result.
* Sparse elimination of a big component gives up after 2e8 multiply-adds (heavy fill-in, as in a
  component where most states lead to most others); then only the sweeps are left.
* A branching component (an action takes an input from a state of its own component: donors that
  need each other, an output recycled as a donor) starts with sweeps from zero. Policy iteration
  (dense, or sparse above `direct_solve_limit`) takes over from the first certificate, so a stiff
  component finishes; a component whose value is infinite is declared so by the mass-closed
  pre-check, or when a value rises above `value_ceiling` (the state is dead and the component is
  solved again without it). A component that is critical through weights (rho exactly 1 with
  the mass leaking) rises linearly, reaches neither, and is reported as unresolved: `ConvergenceError`
  with an infinite `error_bound` (ADR-0022).
"""

import math
from array import array
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from numbers import Integral, Real

from ._certify import ConvergenceError, rounding_allowance
from ._component import backup_single, build_bellman, solve_cyclic
from ._graph import Graph, build_graph, proper_states
from ._model import Action, Model
from ._scc import strongly_connected_components


@dataclass(frozen=True, slots=True)
class Solution[S]:
    """What `solve` returns.

    `values` holds the expected remaining cost of every reachable state: 0.0 for goals and
    `math.inf` for states with no proper policy, for states whose every policy costs infinity
    (a policy that needs two copies of what it makes, ADR-0022) and for states declared dead by
    the `value_ceiling`. `policy` maps each reachable non-goal state with
    a finite value to its original action (true weights, self-loop included; rebuilt from the
    solver's compact storage, so repeated successors of the offered action are merged into one
    outcome and zero-weight outcomes are dropped). `error_bound` is a
    certified relative bound: for every finite value, V(s) * (1 - error_bound) <= V*(s) <=
    V(s) * (1 + error_bound). It includes the float64 rounding of the probabilities, an
    amplification of about epsilon * value / g, so it may exceed the `tolerance` asked for, and it
    is `math.inf` for a component whose upper side cannot be certified (values are still returned).
    With a `value_ceiling` the bound is relative to the model without the states the ceiling
    declared dead.

    An action's `extra_inputs` are states whose value is paid on every attempt (ADR-0022); they
    make the dependency graph of the components, so a donor is solved before the action that uses
    it, and an action with a dead input is dead. A repeated input is one input with several
    copies: the policy's action lists the distinct inputs grouped at the first position of each.
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
    value_ceiling: float = 1e12,
) -> Solution[S]:
    """Minimise the mean cost to a goal from every state reachable from `starts`.

    `tolerance` is the stopping threshold on each cyclic component's own certified relative
    error; components of at most `direct_solve_limit` states are solved by policy iteration
    first (0 forces value iteration everywhere). A larger component gets 300 sweeps; if they do
    not reach `tolerance` and `max_sweeps` allows them, it is solved by sparse policy iteration
    (exact elimination, so a stiff component of thousands of states needs no 1e5 sweeps), and any
    remaining sweeps refine that. Raises `ConvergenceError` when a component cannot reach
    `tolerance` within `max_sweeps` sweeps; its message names the component, and `error_bound` is
    infinite when it never had an upper certificate (a component critical through weights, which
    neither the pre-check nor the ceiling decides).

    A component where an input lies in the component itself (a branching component) is swept from
    zeros; policy iteration starts from the greedy policy at the first sweep with an upper
    certificate (dense up to `direct_solve_limit` states, sparse above it after 300 sweeps; 0 means
    sweeps only). `value_ceiling` (a real above 0, `math.inf` for none) applies to those
    components only: a state whose value rises above it is declared dead, value `inf`, and so is
    every action that uses it as an outcome or an input; the component is then solved again
    without it (the components already finished are not solved again). The certified bound is
    relative to that model. The default 1e12 is in the price unit of the model.
    """
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
    if (
        isinstance(value_ceiling, bool)
        or not isinstance(value_ceiling, Real)
        or not value_ceiling > 0  # false for NaN too
    ):
        raise ValueError(f"value_ceiling must be a real above zero (math.inf for none), got {value_ceiling!r}")
    graph = build_graph(model, starts)
    count = len(graph.states)

    value = [math.inf] * count
    lo = [1.0] * count
    hi = [1.0] * count
    choice = [-1] * count
    done = [False] * count  # settled for good: kept across the restarts that follow a ceiling
    total_error = 0.0
    banned: set[int] = set()
    while True:
        alive, in_y = proper_states(graph, frozenset(banned))
        offsets, edges = _retained_edges(graph, alive, in_y)
        roots = (state for state in range(count) if in_y[state])
        restart = False
        for component in strongly_connected_components(offsets, edges, roots):
            if done[component[0]]:  # downstream of every banned state, so it cannot change
                continue
            if len(component) == 1 and graph.goal[component[0]]:
                value[component[0]] = 0.0
                done[component[0]] = True
                continue
            bellman = build_bellman(graph, alive, component, value, lo, hi)
            rho = rounding_allowance(bellman.terms)
            if len(component) == 1:
                value[component[0]], choice[component[0]] = backup_single(bellman)
                lower = upper = 1.0
                converged = True
            else:
                result = solve_cyclic(bellman, tolerance, direct_solve_limit, max_sweeps, value_ceiling)
                if result.diverged:  # dead: ban them, then solve what is left of the component again
                    banned.update(component[local] for local in result.diverged)
                    restart = True
                    break
                for state, found, action in zip(component, result.values, result.choice):
                    value[state], choice[state] = found, action
                lower, upper, converged = result.lower, result.upper, result.converged
            low = bellman.low_d * lower * (1.0 - rho)
            high = bellman.high_d * upper * (1.0 + rho)
            for state in component:
                lo[state], hi[state] = low, high
                done[state] = True
            total_error = max(total_error, 1.0 - low, high - 1.0)
            if not converged:
                raise ConvergenceError(
                    f"{_describe(graph, component)} did not reach tolerance {tolerance} "
                    f"within {max_sweeps} sweeps",
                    total_error,
                )
        if not restart:  # every restart bans a state that was in Y, so the loop ends
            break

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


def _retained_edges(graph: Graph, alive: list[bool], in_y: list[bool]) -> tuple[array, array]:
    """The state graph over the retained actions only, for the components."""
    offsets, edges = array("q", [0]), array("i")
    targets, tstart, first = graph.targets, graph.tstart, graph.first
    inputs, istart = graph.inputs, graph.istart
    for state in range(len(graph.states)):
        if in_y[state]:
            for k in range(first[state], first[state + 1]):
                if alive[k]:
                    edges.extend(targets[tstart[k] : tstart[k + 1]])
                    if inputs:  # inputs are dependency edges too: a donor in a cycle joins it
                        edges.extend(inputs[istart[k] : istart[k + 1]])
        offsets.append(len(edges))
    return offsets, edges


def _describe(graph: Graph, component: list[int]) -> str:
    """The component named for an error: its size and its first three states by `repr`."""
    names = []
    for s in component[:3]:
        try:
            text = repr(graph.states[s])
        except Exception:  # a state whose repr fails must not hide the ConvergenceError
            text = f"<state {s}>"
        names.append(text if len(text) <= 60 else text[:57] + "...")
    more = len(component) - len(names)
    return f"a component of {len(component)} states ({', '.join(names)}{f' and {more} more' if more else ''})"
