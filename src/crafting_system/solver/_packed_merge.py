"""The exact merge of a packed graph: the coarsest partition with the same futures, and the quotient (ticket #374).

Two states are in one CLASS when they have the same goal status and the same set of (cost, distribution over classes)
pairs, a dearer action with the same distribution of a state being dropped (it is never chosen). This is lumpability with
costs: the optimal value of a state, and the mean, the odds and the quantiles of any policy that picks the same pair in
the members of a class, are a function of the class. Merging changes no answer (ADR-0063 point 1; measured on R05, R10,
R11, R12, R13, S13 and R08 with the Alchemy to 1e-12 in ticket #312).

The partition is found by refinement from {goals, the rest}: each round gives every kernel its distribution over the
current classes (successors grouped by class, weights added, divided by their gcd), gives every state the sorted pairs
(distribution, cheapest cost), and splits the classes by that signature. The refinement only splits, so it stops when a
round splits nothing. Distributions and signatures are compared as exact integer bytes (a big kernel's as a tuple of exact Python
integers, #868), never as hashes.

The quotient has one state per class and the actions of its first member: the pairs above, with the cheapest offer tag.

THE CHECK OF A MERGE (`lumps_exactly`, #1412). The refinement builds the quotient from the first member of each class; `lumps_exactly` checks,
on the graph itself and trusting neither the refinement nor `cls` nor `kernel_map`, that the quotient is a true lumping, all in integers or
in the bits of the costs (never in floats measured against each other):

1. every state has the goal status of its class;
2. every kernel `k` of the graph, its successors' weights added per class and divided by their gcd, has exactly the classes and the integer
   weights of the quotient's kernel `kernel_map[k]`; a chance is weight over total (`_packed`), so the two kernels give every class the same
   chance, as rational numbers;
3. every state that is not a goal has, over its actions, the same set of pairs (kernel of the quotient, cheapest cost of its actions that map
   to that kernel) as its class has in the quotient, the costs compared as the same 64 bits.

Why a certificate of the quotient is then one of the whole graph. Write `T` and `Tq` for the exact Bellman operators (minimum over actions of
cost plus the chance-weighted values of the successors) of the graph and of the quotient, and `L` for copying a value of each class to its
members. By 2 an action of `s` mapped to the quotient's kernel `q` has, on any `L v`, the exact sum `P_q v`; by 3 the actions of `s` reach the
same kernels as those of its class at the same cheapest costs (a dearer action to the same kernel never sets a minimum); by 1 the goals agree.
So `T (L v) = L (Tq v)` term by term, in exact arithmetic. Then:

- the optimum: a policy of the quotient copied to the members is a policy of the graph with the same law of costs and of reaching a goal (by
  2 and 3 the class of the next state has the same chances whatever member the run is in), so `V* <= L Vq*`; any policy of the graph, even one
  that remembers its past and draws at random, read through the classes is one of the quotient with the same law (by 2, the class of the next
  state depends only on the kernel taken), so `V* >= L Vq*`; hence `V* = L Vq*`, and the states with a proper policy are the members of the
  classes with one;
- the plan: `solve_packed.lift_policy` gives each member its cheapest action into the kernel chosen for its class, by 3 at the cost of the
  quotient's action or less, so the plan's value on the graph is at most `L` of the quotient plan's value (equal, as the quotient keeps one
  action, the cheapest, per class and kernel).

A certificate of the quotient states `lower * vq <= Vq* <= Vq^mu <= upper * vq` for its values `vq` and its plan `mu`, each a statement on the
exact quotient (its float measure allows for its own roundings); copied by `L`, each side is the same statement of the graph, of the values
`L vq` and of the lifted plan. Nothing about the size of the values enters: a class whose members hand the run to each other, a cycle of many
states on the graph, is one state with a self-loop on the quotient, whose stay the quotient's measure divides out.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ._certify import ConvergenceError
from ._packed import BIG_TOTAL, PackedGraph, assemble, expand_ranges, kernel_chunks

_INT64_LIMIT = 1 << 63


@dataclass(frozen=True, slots=True, eq=False)
class Classes:
    """The exact classes of a graph.

    `cls[s]` is the class of state `s` (0..count-1); `rounds` the refinement rounds run (the last one split nothing).
    """

    cls: np.ndarray
    count: int
    rounds: int


def _big_signature(graph: PackedGraph, kernel: int, blk: np.ndarray):
    """(signature, sorted block ids, reduced sums) of a big kernel: Python integers all the way.

    The signature is the bytes of int64 pairs when the reduced sums fit them and add up to less than `BIG_TOTAL` (then the distribution
    is one an ordinary kernel can have, and it gets the same key as that kernel), else the tuple of
    (block, sum) pairs itself: exact integers compared and hashed as integers, never turned into decimal text. A kernel's weights are on
    the common denominator of its chances, which grows with every distinct denominator (#868: a Chaos Orb kernel of 148,436 successors
    whose chances have at most 490 bits each has a common denominator of 22,965 bits), so a weight can have thousands of digits; text
    is quadratic in them and refused past 4,300 digits. A tuple never equals a bytes key, so the two forms cannot collide.
    """
    lo, hi = int(graph.k_ptr[kernel]), int(graph.k_ptr[kernel + 1])
    sums: dict[int, int] = {}
    for state, weight in zip(graph.k_succ[lo:hi].tolist(), graph.k_big[kernel]):
        block = int(blk[state])
        sums[block] = sums.get(block, 0) + weight
    divisor = math.gcd(*sums.values())
    items = sorted((block, total // divisor) for block, total in sums.items())
    if all(total < _INT64_LIMIT for _, total in items) and sum(total for _, total in items) < BIG_TOTAL:
        inter = np.array([x for item in items for x in item], dtype=np.int64)
        return inter.tobytes(), [b for b, _ in items], [t for _, t in items]
    return tuple(items), [b for b, _ in items], tuple(t for _, t in items)  # a total of 2^62 or more stays exact Python ints


def kernel_distributions(graph: PackedGraph, blk: np.ndarray, nblk: int, keep_runs: bool = False):
    """The id of every kernel's distribution over the blocks `blk` (equal ids = equal distributions).

    Returns `(ids, runs)`; with `keep_runs`, `runs` lists for each new id (in id order) the pair
    `(block ids int32, reduced weights)` of the first kernel that has it (weights an int64 array, or a tuple of Python
    ints when they do not fit), else `runs` is empty.
    """
    count = graph.num_kernels
    ids = np.empty(count, dtype=np.int64)
    seen: dict[bytes | tuple, int] = {}
    runs: list = []
    k_ptr = graph.k_ptr
    big = graph.k_big
    for k0, k1 in kernel_chunks(k_ptr):
        lo, hi = int(k_ptr[k0]), int(k_ptr[k1])
        nk = k1 - k0
        sizes = np.diff(k_ptr[k0 : k1 + 1])
        local = np.repeat(np.arange(nk, dtype=np.int64), sizes)
        key = local * nblk + blk[graph.k_succ[lo:hi]]
        order = np.argsort(key, kind="stable")
        sorted_key = key[order]
        weights = graph.k_wt[lo:hi][order]
        starts = np.flatnonzero(np.concatenate(([True], sorted_key[1:] != sorted_key[:-1])))
        sums = np.add.reduceat(weights, starts)
        run_kernel = sorted_key[starts] // nblk
        run_block = sorted_key[starts] - run_kernel * nblk
        run_ptr = np.searchsorted(run_kernel, np.arange(nk + 1))
        divisor = np.gcd.reduceat(sums, run_ptr[:-1])
        divisor[divisor == 0] = 1  # a big kernel's weights are zero here; it is redone below
        reduced = sums // np.repeat(divisor, np.diff(run_ptr))
        inter = np.empty(2 * len(reduced), dtype=np.int64)
        inter[0::2] = run_block
        inter[1::2] = reduced
        text = inter.tobytes()
        cuts = (run_ptr * 16).tolist()
        pointers = run_ptr.tolist()
        for j in range(nk):
            kernel = k0 + j
            if kernel in big:
                signature, blocks, found_sums = _big_signature(graph, kernel, blk)
                a = b = 0
            else:
                signature = text[cuts[j] : cuts[j + 1]]
                a, b = pointers[j], pointers[j + 1]
            found = seen.get(signature)
            if found is None:
                found = seen[signature] = len(seen)
                if keep_runs:
                    if kernel in big:
                        sums_out = found_sums if isinstance(found_sums, tuple) else np.array(found_sums, dtype=np.int64)
                        runs.append((np.array(blocks, dtype=np.int32), sums_out))
                    else:
                        runs.append((run_block[a:b].astype(np.int32), reduced[a:b].copy()))
            ids[kernel] = found
    return ids, runs


def _next_blocks(graph: PackedGraph, blk: np.ndarray, nblk: int, act_state: np.ndarray) -> tuple[np.ndarray, int]:
    """One refinement round: the new block of every state (goals 0, the others 1..) and the number of distinct blocks."""
    ids, _ = kernel_distributions(graph, blk, nblk)
    n = graph.n
    new = np.zeros(n, dtype=np.int64)
    goal = graph.goal
    if graph.num_actions:
        dist = ids[graph.act_kernel]
        cost_bits = graph.act_cost.view(np.int64)
        order = np.lexsort((cost_bits, dist, act_state))
        s_o, d_o, c_o = act_state[order], dist[order], cost_bits[order]
        first = np.concatenate(([True], (s_o[1:] != s_o[:-1]) | (d_o[1:] != d_o[:-1])))
        s_k, d_k, c_k = s_o[first], d_o[first], c_o[first]
        pointers = np.searchsorted(s_k, np.arange(n + 1)).tolist()
        inter = np.empty(2 * len(d_k), dtype=np.int64)
        inter[0::2] = d_k
        inter[1::2] = c_k
        text = inter.tobytes()
    else:
        pointers = [0] * (n + 1)
        text = b""
    found: dict[tuple, int] = {}
    blocks = blk.tolist()
    flags = goal.tolist()
    out = [0] * n
    for s in range(n):
        if flags[s]:
            continue
        signature = (blocks[s], text[pointers[s] * 16 : pointers[s + 1] * 16])
        value = found.get(signature)
        if value is None:
            value = found[signature] = len(found) + 1
        out[s] = value
    new[:] = out
    return new, len(found) + (1 if flags and any(flags) else 0)


def exact_classes(
    graph: PackedGraph, progress: Callable[[str], None] | None = None, max_rounds: int = 10_000, most: int | None = None
) -> Classes | None:
    """The coarsest exact partition of `graph` (see the module docstring); with `most`, None as soon as it has more classes than that (a round
    only splits classes, so the count of a round is at most the final count: `_packed_exact` asks for a small quotient, #1380)."""
    say = progress or (lambda _text: None)
    began = time.perf_counter()
    n = graph.n
    act_state = graph.action_state()
    blk = np.where(graph.goal, 0, 1).astype(np.int64)
    count = len(np.unique(blk))
    rounds = 0
    while True:
        if rounds >= max_rounds:
            raise ConvergenceError(f"the exact merge did not settle in {max_rounds} rounds ({count:,} classes so far)", float("inf"))
        rounds += 1
        new, new_count = _next_blocks(graph, blk, int(blk.max()) + 1 if n else 1, act_state)
        say(f"merge round {rounds}: {new_count:,} classes ({time.perf_counter() - began:.1f} s)")
        if new_count == count:
            break
        if most is not None and new_count > most:
            return None
        blk, count = new, new_count
    unique, cls = np.unique(blk, return_inverse=True)
    return Classes(cls.astype(np.int64), len(unique), rounds)


def identity_classes(graph: PackedGraph) -> Classes:
    """Every state its own class (the graph unmerged): `solve_packed(merge=False)`."""
    return Classes(np.arange(graph.n, dtype=np.int64), graph.n, 0)


def quotient(graph: PackedGraph, classes: Classes) -> tuple[PackedGraph, np.ndarray]:
    """The packed graph of the classes and the kernel map (kernel of `graph` -> kernel of the quotient).

    One state per class; its actions are the pairs (distribution, cheapest cost) of its first member.
    """
    cls, ncls = classes.cls, classes.count
    if classes.rounds == 0 and ncls == graph.n:  # the identity: nothing to rebuild
        return graph, np.arange(graph.num_kernels, dtype=np.int64)
    first = np.unique(cls, return_index=True)[1].astype(np.int64)
    goal = graph.goal[first]
    # kernels of the quotient: the reduced distributions over the classes
    kernel_map, runs = kernel_distributions(graph, cls, max(ncls, 1), keep_runs=True)
    kernel_succ = [r[0] for r in runs]
    kernel_wt = [r[1] for r in runs]
    # actions of the quotient: those of the first member of each class, one per distinct distribution (the cheapest)
    counts = np.diff(graph.act_ptr)[first]
    counts[goal] = 0
    take = expand_ranges(graph.act_ptr[first], counts)
    owner = np.repeat(np.arange(ncls, dtype=np.int64), counts)
    kernel = kernel_map[graph.act_kernel[take]]
    cost = graph.act_cost[take]
    tag = graph.act_tag[take]
    order = np.lexsort((take, cost, kernel, owner))  # per class, per distribution: the cheapest first
    owner_o, kernel_o = owner[order], kernel[order]
    keep = np.concatenate(([True], (owner_o[1:] != owner_o[:-1]) | (kernel_o[1:] != kernel_o[:-1])))[: len(order)]
    pick = order[keep]
    act_owner = owner[pick]
    act_ptr = np.concatenate(([0], np.cumsum(np.bincount(act_owner, minlength=ncls)))).astype(np.int64)
    reduced = assemble(
        goal.copy(),
        act_ptr,
        tag[pick].astype(np.int32),
        cost[pick].copy(),
        kernel[pick].astype(np.int32),
        kernel_succ,
        kernel_wt,
    )
    return reduced, kernel_map


def lumps_exactly(graph: PackedGraph, cls: np.ndarray, reduced: PackedGraph, kernel_map: np.ndarray) -> bool:
    """Whether `reduced` is the exact quotient of `graph` by the classes `cls` with `kernel_map` (#1412): checked on `graph` itself, in integers.

    Three things, each from the arrays of both graphs and none from the refinement that found the classes:

    1. every state has the goal status of its class;
    2. every kernel `k` of `graph`, its weights added per class of its successors and divided by their gcd, is the kernel `kernel_map[k]` of
       `reduced` (the same classes, the same integer weights: so the same chances, exactly);
    3. every state that is not a goal has, over its actions, the same set of pairs (kernel of `reduced`, cheapest cost of the actions that map to
       it) as the actions of its class in `reduced`.

    Then a certificate of values on `reduced` is one of the same values copied to the members of `graph` (the module docstring, "The check of
    a merge", gives the argument).
    """
    n, m = graph.n, reduced.n
    if len(cls) != n or (n and (int(cls.min()) < 0 or int(cls.max()) >= m)) or len(kernel_map) != graph.num_kernels:
        return False
    if not np.array_equal(graph.goal, reduced.goal[cls]):
        return False
    if graph.num_kernels and (int(kernel_map.min()) < 0 or int(kernel_map.max()) >= reduced.num_kernels):
        return False
    if not _kernels_lump(graph, cls, reduced, kernel_map):
        return False
    return _actions_lump(graph, cls, reduced, kernel_map)


def _reduced_pairs(succ: np.ndarray, wt: list[int]) -> list[tuple[int, int]]:
    divisor = math.gcd(*wt) or 1
    return sorted((int(s), w // divisor) for s, w in zip(succ.tolist(), wt))


def _kernels_lump(graph: PackedGraph, cls: np.ndarray, reduced: PackedGraph, kernel_map: np.ndarray) -> bool:
    """Point 2 of `lumps_exactly`: int64 arrays for the kernels of `graph` and `reduced` that hold their weights there (totals below `BIG_TOTAL`,
    so no sum overflows), Python integers for the others."""
    big = set(graph.k_big) | {k for k, q in enumerate(kernel_map.tolist()) if q in reduced.k_big}
    k_ptr = graph.k_ptr
    q_sizes = reduced.kernel_sizes()
    width = max(reduced.n, 1)
    for k0, k1 in kernel_chunks(k_ptr):
        lo, hi = int(k_ptr[k0]), int(k_ptr[k1])
        nk = k1 - k0
        sizes = np.diff(k_ptr[k0 : k1 + 1])
        local = np.repeat(np.arange(nk, dtype=np.int64), sizes)
        key = local * width + cls[graph.k_succ[lo:hi]]
        order = np.argsort(key, kind="stable")
        sorted_key = key[order]
        starts = np.flatnonzero(np.concatenate(([True], sorted_key[1:] != sorted_key[:-1]))) if hi > lo else np.zeros(0, dtype=np.int64)
        sums = np.add.reduceat(graph.k_wt[lo:hi][order], starts) if hi > lo else np.zeros(0, dtype=np.int64)
        run_kernel = sorted_key[starts] // width
        run_class = sorted_key[starts] - run_kernel * width
        run_ptr = np.searchsorted(run_kernel, np.arange(nk + 1))
        counts = np.diff(run_ptr)
        mapped = kernel_map[k0:k1]
        plain = np.array([k0 + j not in big for j in range(nk)], dtype=bool)
        if np.any(plain & (counts != q_sizes[mapped])):
            return False
        divisor = np.gcd.reduceat(sums, run_ptr[:-1]) if len(sums) else np.zeros(nk, dtype=np.int64)
        divisor = np.where(counts > 0, divisor, 1)
        divisor[divisor == 0] = 1
        reduced_wt = sums // np.repeat(divisor, counts)
        # the kernel of `reduced` each run is compared with, its edges sorted by class
        q_idx = expand_ranges(reduced.k_ptr[mapped], np.where(plain, q_sizes[mapped], 0))
        q_kernel = np.repeat(np.arange(nk, dtype=np.int64), np.where(plain, q_sizes[mapped], 0))
        q_succ = reduced.k_succ[q_idx].astype(np.int64)
        q_order = np.lexsort((q_succ, q_kernel))
        keep = np.repeat(plain, counts)
        if not (np.array_equal(run_class[keep], q_succ[q_order]) and np.array_equal(reduced_wt[keep], reduced.k_wt[q_idx][q_order])):
            return False
        for j in np.flatnonzero(~plain).tolist():
            kernel = k0 + j
            klo, khi = int(k_ptr[kernel]), int(k_ptr[kernel + 1])
            totals: dict[int, int] = {}
            for state, weight in zip(cls[graph.k_succ[klo:khi]].tolist(), graph.kernel_weights(kernel)):
                totals[state] = totals.get(state, 0) + weight
            q = int(mapped[j])
            want = _reduced_pairs(reduced.k_succ[reduced.k_ptr[q] : reduced.k_ptr[q + 1]], list(reduced.kernel_weights(q)))
            if _reduced_pairs(np.array(list(totals), dtype=np.int64), list(totals.values())) != want:
                return False
    return True


def _actions_lump(graph: PackedGraph, cls: np.ndarray, reduced: PackedGraph, kernel_map: np.ndarray) -> bool:
    """Point 3 of `lumps_exactly`: per state, the sorted pairs (kernel of `reduced`, cheapest cost) against those of its class."""

    def pairs(g: PackedGraph, kernel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        owner = g.action_state().astype(np.int64)
        live = ~g.goal[owner]
        owner, kernel, cost = owner[live], kernel[live], g.act_cost[live]
        order = np.lexsort((cost, kernel, owner))
        owner, kernel, cost = owner[order], kernel[order], cost[order]
        first = np.concatenate(([True], (owner[1:] != owner[:-1]) | (kernel[1:] != kernel[:-1]))) if len(owner) else np.zeros(0, dtype=bool)
        owner, kernel, cost = owner[first], kernel[first], cost[first]
        return np.searchsorted(owner, np.arange(g.n + 1)), kernel, cost

    s_ptr, s_kernel, s_cost = pairs(graph, kernel_map[graph.act_kernel].astype(np.int64))
    c_ptr, c_kernel, c_cost = pairs(reduced, reduced.act_kernel.astype(np.int64))
    s_count, c_count = np.diff(s_ptr), np.diff(c_ptr)
    if not np.array_equal(s_count, c_count[cls]):
        return False
    idx = expand_ranges(c_ptr[:-1][cls], s_count)
    return bool(np.array_equal(s_kernel, c_kernel[idx]) and np.array_equal(s_cost.view(np.int64), c_cost[idx].view(np.int64)))
