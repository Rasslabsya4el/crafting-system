"""The exact merge of a packed graph: the coarsest partition with the same futures, and the quotient (ticket #374).

Two states are in one CLASS when they have the same goal status and the same set of (cost, distribution over classes)
pairs, a dearer action with the same distribution of a state being dropped (it is never chosen). This is lumpability with
costs: the optimal value of a state, and the mean, the odds and the quantiles of any policy that picks the same pair in
the members of a class, are a function of the class. Merging changes no answer (ADR-0063 point 1; measured on R05, R10,
R11, R12, R13, S13 and R08 with the Alchemy to 1e-12 in ticket #312).

The partition is found by refinement from {goals, the rest}: each round gives every kernel its distribution over the
current classes (successors grouped by class, weights added, divided by their gcd), gives every state the sorted pairs
(distribution, cheapest cost), and splits the classes by that signature. The refinement only splits, so it stops when a
round splits nothing. Distributions and signatures are compared as exact integer bytes, never as hashes.

The quotient has one state per class and the actions of its first member: the pairs above, with the cheapest offer tag.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ._packed import PackedGraph, assemble, expand_ranges, kernel_chunks

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
    """(signature bytes, sorted block ids, reduced sums) of a big kernel: Python integers all the way."""
    lo, hi = int(graph.k_ptr[kernel]), int(graph.k_ptr[kernel + 1])
    sums: dict[int, int] = {}
    for state, weight in zip(graph.k_succ[lo:hi].tolist(), graph.k_big[kernel]):
        block = int(blk[state])
        sums[block] = sums.get(block, 0) + weight
    divisor = math.gcd(*sums.values())
    items = sorted((block, total // divisor) for block, total in sums.items())
    if all(total < _INT64_LIMIT for _, total in items):
        inter = np.array([x for item in items for x in item], dtype=np.int64)
        return inter.tobytes(), [b for b, _ in items], [t for _, t in items]
    return b"B" + repr(items).encode(), [b for b, _ in items], tuple(t for _, t in items)


def kernel_distributions(graph: PackedGraph, blk: np.ndarray, nblk: int, keep_runs: bool = False):
    """The id of every kernel's distribution over the blocks `blk` (equal ids = equal distributions).

    Returns `(ids, runs)`; with `keep_runs`, `runs` lists for each new id (in id order) the pair
    `(block ids int32, reduced weights)` of the first kernel that has it (weights an int64 array, or a tuple of Python
    ints when they do not fit), else `runs` is empty.
    """
    count = graph.num_kernels
    ids = np.empty(count, dtype=np.int64)
    seen: dict[bytes, int] = {}
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
    graph: PackedGraph, progress: Callable[[str], None] | None = None, max_rounds: int = 10_000
) -> Classes:
    """The coarsest exact partition of `graph` (see the module docstring)."""
    say = progress or (lambda _text: None)
    began = time.perf_counter()
    n = graph.n
    act_state = graph.action_state()
    blk = np.where(graph.goal, 0, 1).astype(np.int64)
    count = len(np.unique(blk))
    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        new, new_count = _next_blocks(graph, blk, int(blk.max()) + 1 if n else 1, act_state)
        say(f"merge round {rounds}: {new_count:,} classes ({time.perf_counter() - began:.1f} s)")
        if new_count == count:
            break
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
    keep = np.concatenate(([True], (owner_o[1:] != owner_o[:-1]) | (kernel_o[1:] != kernel_o[:-1])))
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
