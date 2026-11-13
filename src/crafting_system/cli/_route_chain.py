"""The policy of a packed plan, or a given route read on its graph, as the item-state `Chain` the route page is made from (ticket #466).

A packed plan above `VIEW_FROM_STATES` item states is shown by its lumped chain: one shown member per block, exact for what a block
pays and for the blocks it leads to, so exact for the chances, uses and costs of a step, but not for a statement about an item (a
wanted mod lost, the tiers a draw can add): two members of a block can hold different items. The page therefore reads the item
states themselves. They are the states the policy reaches in the walked graph (R14: 87,251 of them, with about a million
transitions between them), held as arrays: for each state its action's label and price, and the kernel it moves by. The
kernels the policy uses are held once each (`graph.k_succ` renumbered to the chain's own numbering, `k_wt`, `k_prob`), not
copied to every state that shares one (R04: 15,003 states, 4,038 kernels; ticket #689). No `Action` is built except the first of each step.

The states are numbered breadth first from the start, a level at a time and by graph number within a level, which is what makes
the numbering of the steps deterministic. `reasons` says why a reachable non-goal state has no action (a gap of a given route).
"""

from collections.abc import Mapping, Sequence

import numpy as np

from crafting_system.abstraction import CompressedState
from crafting_system.solver import Action, Outcome
from crafting_system.solver._packed import expand_ranges
from crafting_system.planner import PackedPolicy, Walked

from ._route_flow import Chain, Kernels, chain_of_policy, empty_chain


def packed_chain(
    walked: Walked,
    action: np.ndarray,
    label_ids: np.ndarray,
    names: Sequence[str],
    cost: np.ndarray,
    reasons: Mapping[int, str] | None = None,
) -> Chain[CompressedState]:
    """The chain of the policy that takes the graph action `action[i]` at state `i` (-1: none), from the start (state 0).

    `label_ids[i]` indexes `names` for the label of the action taken at state `i`, `cost[i]` is its price, `reasons` maps a graph
    state with no action to why.
    """
    graph = walked.graph
    if graph.goal[0]:
        return empty_chain()
    reasons = reasons or {}
    n = graph.n
    ksize = graph.kernel_sizes()
    seen = np.zeros(n, dtype=bool)
    seen[0] = True
    levels = [np.zeros(1, dtype=np.int64)]
    frontier = levels[0]
    while True:
        acting = frontier[(action[frontier] >= 0) & ~graph.goal[frontier]]
        if not acting.size:
            break
        kernels = np.unique(graph.act_kernel[action[acting]])
        successors = np.unique(graph.k_succ[expand_ranges(graph.k_ptr[kernels], ksize[kernels])])
        fresh = successors[~seen[successors]].astype(np.int64)
        if not fresh.size:
            break
        seen[fresh] = True
        levels.append(fresh)
        frontier = fresh
    reached = np.concatenate(levels)
    is_goal = graph.goal[reached]
    plain, goals = reached[~is_goal], reached[is_goal]
    m = len(plain)
    position = np.full(n, -1, dtype=np.int64)
    position[plain] = np.arange(m)
    position[goals] = m + np.arange(len(goals))

    acting = action[plain] >= 0
    chosen = action[plain[acting]]
    used, slot = np.unique(graph.act_kernel[chosen], return_inverse=True)  # each kernel once, whatever the states that share it (#689)
    sizes = ksize[used]
    edge = expand_ranges(graph.k_ptr[used], sizes)
    kernel = np.full(m, -1, dtype=np.int64)
    kernel[acting] = slot.reshape(-1)
    big = {k: graph.k_big[int(g)] for k, g in enumerate(used.tolist()) if int(g) in graph.k_big}
    table = Kernels(np.concatenate(([0], np.cumsum(sizes))).astype(np.int64), position[graph.k_succ[edge]], graph.k_wt[edge], graph.k_prob[edge], big)

    dead = sorted({reasons.get(int(g)) or "" for g in plain[~acting].tolist()})
    dead_id = {reason: len(names) + k for k, reason in enumerate(dead)}
    key = np.where(acting, label_ids[plain], 0).astype(np.int64)
    for i in np.flatnonzero(~acting).tolist():
        key[i] = dead_id[reasons.get(int(plain[i])) or ""]
    keys = tuple(("action", name) for name in names) + tuple(("none", reason or None) for reason in dead)

    def action_of(i: int) -> Action[CompressedState]:
        g = int(plain[i])
        kernel = int(graph.act_kernel[action[g]])
        successors = graph.k_succ[graph.k_ptr[kernel] : graph.k_ptr[kernel + 1]].tolist()
        weights = graph.kernel_weights(kernel)
        outcomes = tuple(Outcome(walked.states[s], int(w)) for s, w in zip(successors, weights))
        return Action(names[int(label_ids[g])], float(cost[g]), outcomes)

    return Chain(
        [walked.states[g] for g in plain.tolist()],
        [walked.states[g] for g in goals.tolist()],
        key,
        keys,
        cost[plain],
        kernel,
        table,
        action_of,
    )


def chain_of_plan(plan) -> Chain[CompressedState]:
    """The item-state chain of a plan's own policy: from the walked graph for a plan shown by its lumped chain, else from the policy mapping."""
    if plan.lumped:
        return chain_of_packed_policy(plan.policy)
    return chain_of_policy(plan.start, plan.policy, plan.is_goal)


def chain_of_packed_policy(policy: PackedPolicy) -> Chain[CompressedState]:
    """The chain of the optimal policy of a packed plan (made once: the plan's limits and the page both read it)."""
    cached = getattr(policy, "_item_chain", None)
    if cached is None:
        cached = policy._item_chain = _chain_of_packed_policy(policy)  # type: ignore[attr-defined]
    return cached


def _chain_of_packed_policy(policy: PackedPolicy) -> Chain[CompressedState]:
    walked = policy.walked
    graph = walked.graph
    action = policy.action_array
    shaped = np.maximum(action, 0)
    return packed_chain(
        walked,
        action,
        graph.act_tag[shaped].astype(np.int64),
        [priced.label for priced in walked.offers],
        graph.act_cost[shaped],
    )


def chain_of_route(
    walked: Walked, chosen: np.ndarray, labels: Mapping[int, str], cost: np.ndarray, gaps: Sequence[tuple[int, str]]
) -> Chain[CompressedState]:
    """The chain of a given route read on the walked graph: `chosen[i]` the graph action it takes at state `i` (-1: none, a gap), `labels[i]` the offer it names, `cost[i]` its price."""
    names = sorted(set(labels.values()))
    number = {name: k for k, name in enumerate(names)}
    label_ids = np.zeros(walked.graph.n, dtype=np.int64)
    for i, label in labels.items():
        label_ids[i] = number[label]
    return packed_chain(walked, chosen, label_ids, names, cost, dict(gaps))
